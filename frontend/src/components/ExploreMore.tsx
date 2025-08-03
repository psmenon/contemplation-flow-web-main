
import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import BaseModal from "./BaseModal";

interface ExploreMoreProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectQuestion: (question: string) => void;
  questions?: string[];
  inline?: boolean;
}

const ExploreMore = ({ isOpen, onClose, onSelectQuestion, questions: propQuestions, inline = false }: ExploreMoreProps) => {
  const [questions, setQuestions] = useState(
    propQuestions && propQuestions.length > 0
      ? propQuestions
      : [
        "Question #1 Card",
        "Question #2 Card",
        "Question #3 Card"
      ]
  );

  // Update questions when propQuestions changes
  useEffect(() => {
    if (propQuestions && propQuestions.length > 0) {
      setQuestions(propQuestions);
    }
  }, [propQuestions]);

  const generateNewQuestions = () => {
    // If we have prop questions, shuffle them, otherwise use default questions
    if (propQuestions && propQuestions.length > 0) {
      // Shuffle the existing questions
      const shuffled = [...propQuestions].sort(() => Math.random() - 0.5);
      setQuestions(shuffled);
    } else {
      // Use default questions
      setQuestions([
        "How does mindfulness affect daily decision-making?",
        "What role does storytelling play in personal growth?",
        "How can we find meaning in unexpected challenges?"
      ]);
    }
  };

  const modalContent = (
    <>
      <div className="space-y-3 mb-4">
        {questions.map((question, index) => (
          <Button
            key={index}
            onClick={() => onSelectQuestion(question)}
            variant="outline"
            className="w-full p-4 h-auto rounded-2xl border-2 border-gray-200 hover:border-brand-button text-left justify-start"
          >
            {question}
          </Button>
        ))}
      </div>

      {!inline && (
        <div className="border-t pt-6 mt-6">
          <div className="relative">
            <div className="bg-gray-100 rounded-2xl p-4 mb-4">
              <p className="text-gray-700">Question #2 is now here. User can also edit this.</p>
            </div>
            <div className="absolute right-2 top-1/2 transform -translate-y-1/2 flex gap-2">
              <Button
                variant="ghost"
                size="sm"
                className="rounded-full w-12 h-12 bg-yellow-100 text-yellow-600"
              >
                %
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="rounded-full w-12 h-12 bg-orange-100 text-brand-button"
              >
                →
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );

  return (
    <BaseModal
      isOpen={isOpen}
      onClose={onClose}
      title="Here's a few questions that might help you:"
      inline={inline}
      showCloseButton={!inline}
    >
      {modalContent}
    </BaseModal>
  );
};

export default ExploreMore;
